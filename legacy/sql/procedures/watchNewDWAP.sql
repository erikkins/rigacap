-- SqlProcedure: [dbo].[watchNewDWAP]

set nocount on

if @channel=null
	begin
		select @channel = 'F'
	end



--declare @startdate datetime, @enddate datetime
declare @currdate datetime
--select @enddate = getdate()
--select @startdate = dateadd(year,-2, @enddate)
declare @print varchar(200)
declare @sid int, @ticker varchar(10)
declare @watchID int
declare @lastprice money
declare @currprice money, @DWAP money
declare @currvol bigint
declare @avgvol bigint 

select @currdate = convert(varchar,getdate(),101)

select @watchID = watchID
from watch
where procName='WatchNewDWAP'

if @watchID is null
	return -1

exec addWatchHistory @watchID, @currdate

--while @currdate < @enddate
	begin
		if Datepart(dw,@currdate)=1 or datepart(dw,@currdate)=7
			begin
				return 0
				/*
				if datepart(dw,@currdate)=1
					begin
						select @currdate = dateadd(day,1,@currdate)
					end
				else
					begin
						select @currdate = dateadd(day,2,@currdate)
					end
				*/
			end

		--select @print = convert(varchar,@currdate,101)
		--print @print
		declare scur cursor for
			select stockID, ticker from stock where active=1 order by ticker asc

		open scur
		fetch next from scur into @sid, @ticker
		while @@fetch_status=0
			begin				
				--so, on this date, did we pop above the 200DMA?				
				select @currprice = price,
				@currvol = volume
				from stockdata
				where stockID = @sid
				and atwhen = convert(varchar,@currdate,101)

				select top 1 @lastprice = price
				from stockdata
				where stockID = @sid
				and atwhen < @currdate
				order by atwhen desc							

				declare @minprice money
				select @minprice = 25 --was 50 and 35

				declare @minavgvol bigint
				select @minavgvol=500000

				if @lastprice < 50
					begin
						select @minavgvol = 300000
					end

				select @avgvol = avg(volume)
				from stockdata
				where stockID=@sid
				and atwhen between dateadd(year,-1,@currdate) and @currdate

				if @lastprice > @minprice and @currprice > @minprice and @avgvol > @minavgvol  and @currvol >= (@avgvol * 1.5) and @lastprice is not null and @currprice is not null
					begin						
						--OK, we've got something to munch on here
						select @DWAP = dbo.fnDWAP(@sid, @currdate)
						if @dwap is not null and @lastprice < @DWAP and @currprice > @DWAP
							begin
								--if exists (select * from newdwap where stockID=@sid)
								--	begin
								--		update newdwap
								--		set atwhen = @currdate
								--		where stockID=@sid
								--	end
								--else
								--	begin
										insert into newdwap
											select @sid,@currdate,1, null
								--	end
								--select @print = @ticker + ' crossed on ' + convert(varchar,@currdate,101) + ' (' + convert(varchar,@lastprice) + ' < ' + convert(varchar,@DWAP) + ' < ' + convert(varchar,@currprice) + ')'
								--print @print
							end								
					end				
	
			fetch next from scur into @sid, @ticker
			end
		close scur
		deallocate scur
			
	--select @currdate = convert(varchar,dateadd(day,1,@currdate),101)
	end

set nocount off
