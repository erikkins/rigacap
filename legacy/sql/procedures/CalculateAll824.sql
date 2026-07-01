-- SqlProcedure: [dbo].[CalculateAll824]

set nocount on;

--Create a CTE worktable t1 to allow us to refer to the n
--field in order to perform a join
with t1 as (select row_number() over (order by atwhen) n,
		atwhen	,
		price	from stockdata where StockID=@stockID)   
	 select a.n
       ,a.atwhen
       ,a.price       
       ,CAST(null as decimal(8,2)) [8sma]
       ,CAST(null as decimal(8,2)) [34sma]
       --add the close_price from 8 row prior to this one       
       ,CAST(b.price as decimal(8,2)) [8_day_old_close]
       --add the close price from 34 row prior to this one
       ,CAST(c.price as decimal(8,2)) [34_day_old_close]
       into #mod_goog_data	
       from t1 a 
       left join t1 b 
       on a.n - 8 = b.n
       left join t1 c
       on a.n -34 = c.n
       


declare @intervals int, @initial_sum decimal(8,2) 
declare @anchor int, @moving_sum decimal(8,2)
set @intervals = 8

 --Retrieve the initial sum value at row 20 
 select @initial_sum = sum(price)    
  from #mod_goog_data   
   where n <= @intervals

 update t1     
	--case statement to handle @moving_sum variable
    --depending on the value of n
   set @moving_sum = case	when n < @intervals then null		     
							when n = @intervals then @initial_sum		     
							when n > @intervals then 
								@moving_sum + [price] - [8_day_old_close] 		    
							end,	
					[8sma] = @moving_sum/Cast(@intervals as decimal(8,2)),
					@anchor = n    --anchor so that carryover works	
					from #mod_goog_data t1 with (TABLOCKX)	OPTION (MAXDOP 1)
	
	
set @intervals=34
select @initial_sum = sum(price)    
from #mod_goog_data   
 where n <= @intervals

 update t1     
	--case statement to handle @moving_sum variable
    --depending on the value of n
   set @moving_sum = case	when n < @intervals then null		     
							when n = @intervals then @initial_sum		     
							when n > @intervals then 
								@moving_sum + [price] - [34_day_old_close] 		    
							end,	
					[34sma] = @moving_sum/Cast(@intervals as decimal(8,2)),
					@anchor = n    --anchor so that carryover works	
					from #mod_goog_data t1 with (TABLOCKX)	OPTION (MAXDOP 1)	
	
  select atwhen ,price ,[8sma], [34SMA] 
  into #rawdata
  from #mod_goog_data
  order by atwhen asc

create table #tBuy
	(buydate datetime, buyprice decimal(8,2), selldate datetime, sellprice decimal(8,2))

	insert into #tBuy
	select a.atwhen, a.price, null, null 
	from #rawdata a
	inner join #rawdata b on dateadd(day,1,a.atwhen) = b.atwhen
	where a.[8sma] < a.[34SMA]
	and b.[8sma] > a.[34SMA]
	
	 --select atwhen ,price ,[8sma], [34SMA]   
	 --from #mod_goog_data

	
	--now for each buy point, detect the next place where the 8 drops below the 34
	
	declare @curdate datetime, @selldate datetime, @sellprice decimal(8,2)
	
	declare bcur cursor for 
		select buydate from #tBuy	
	
	open bcur
	fetch next from bcur into @curdate
		while @@FETCH_STATUS=0
			begin
				select @selldate=MIN (a.atwhen) from #rawdata a
				inner join #rawdata b on DATEADD(day,1,a.atwhen) = b.atwhen
				where a.[8sma] > a.[34SMA]
				and b.[8sma] < a.[34SMA]
				and a.atwhen > @curdate
				
				select @sellprice = price from #rawdata where atwhen=@selldate
				
				update #tBuy
				set selldate = @selldate, sellprice =@sellprice
				where buydate = @curdate
			
			
			fetch next from bcur into @curdate		
			end
	close bcur
	deallocate bcur
	
	

	
	select * from #tbuy
	drop table #tbuy
	
	drop table #rawdata
	drop table #mod_goog_data
set nocount off
