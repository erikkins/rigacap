-- SqlProcedure: [dbo].[ERIKDWAPBUY]
-- header:
-- CREATE proc [dbo].[ERIKDWAPBUY]

CREATE proc [dbo].[ERIKDWAPBUY]
as
--let's go back one year
set nocount on
declare @startdate datetime, @enddate datetime
declare @currdate datetime
select @enddate = '1/1/2008'
--select @startdate = dateadd(year,-2, @enddate)
select @startdate = '1/1/2007'
declare @print varchar(200)
declare @sid int, @ticker varchar(10)

declare @lastprice money
declare @currprice money, @DWAP money
declare @currvol bigint
declare @avgvol bigint
declare @buyID int
declare @yesterday datetime
declare @audit varchar(1000)
select @yesterday = dateadd(day,-1,getdate())
declare @lastDataDate datetime
declare @retval int

select @currdate = convert(varchar,@startdate,101)

while @currdate < @enddate
	begin
		--if datepart(day, @currdate)=1
		--	begin
				 Print @currdate
		--	end

		if Datepart(dw,@currdate)=1 or datepart(dw,@currdate)=7
			begin
				if datepart(dw,@currdate)=1
					begin
						select @currdate = dateadd(day,1,@currdate)
					end
				else
					begin
						select @currdate = dateadd(day,2,@currdate)
					end
			end



		--select @print = convert(varchar,@currdate,101)
		--print @print
		declare scur cursor for
			select distinct stockID, ticker from stock
			where ticker in
			('AGU','AG','AAPL','ONXX','PCLN','MON','GME','PKX','SIGM','PBRA','FWLT','ACH','VSEA','BGC','GRMN','BHP','DV','SPWR','RIMM','CMI',
			'TYC','MTL','PBR','CRS','WFT','SU','UNP','WCG','BUCY','JBX','CRS','CTRP','DPZ','GMR','GCO','HWCC','KND','NSIT','TMX',
			'NOV','JEC','AMZN','WFR','HON','MRK','MCD','INTC','BIDU','ISRG',
			'ETFC','CFC','CC','MBI','ABK','C','HD','AIG','GM','AXP','LVLT','SBUX','SHLD','VRTX','NTAP'		
			)
			order by ticker asc
			--select stockID, ticker from stock where active=1 order by ticker asc

		open scur
		fetch next from scur into @sid, @ticker
		while @@fetch_status=0
			begin				
					
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
				
				select @avgvol=dbo.fn200Volume(@sid, @currdate)
				/*
				select @avgvol = avg(volume)
				from stockdata
				where stockID=@sid
				and atwhen between dateadd(year,-1,@currdate) and @currdate
				*/
				declare @minavgvol bigint
				select @minavgvol=500000

				if @lastprice < 50
					begin
						select @minavgvol = 300000
					end
				
				
			

				if @lastprice > @minprice and @currprice > @minprice and @lastprice is not null and @currprice is not null and @avgvol > @minavgvol--  and @currvol >= (@avgvol * 1.5) and @lastprice is not null and @currprice is not null				
					begin						
						--OK, we've got something to munch on here
						select @DWAP = dbo.fnDWAP(@sid, @currdate)
						/*
						declare @goodToGo bit
						select @goodToGo = dbo.fn7of10HighVolume(@sid, @currdate)					

						declare @slopeDWAP float, @slope50 float, @slope float

						if @goodToGo = 1
							begin
								select @slopeDWAP = dbo.fnSlopeDWAP(@sid, dateadd(day,-30,@currdate), @currdate) 
								if @slopeDWAP between -0.05 and 0.21
									begin
										select @goodToGo=1
										select @slope50 = dbo.fnSlope50(@sid, dateadd(day,-30,@currdate), @currdate) 
										if @slope50 between -0.07 and 0.25
											begin	
												select @goodToGo=1
												select @slope = dbo.fnSlope(@sid, dateadd(day,-30,@currdate), @currdate) 
												if @slope between -.32 and 0.52
													begin
														select @goodToGo=1
													end
												else
													begin
														select @goodToGo=0
													end
											end
										else
											begin
												select @goodToGo = 0
											end
									end
								else
									begin 
										select @goodToGo=0
									end
							end
						*/
						


						if @dwap is not null and @lastprice < @DWAP and @currprice > @DWAP --and @goodToGo=1 and dbo.fnSmooth(@sid,@currdate)=1 --and dbo.fnDWAP(@sid,@currdate) > dbo.fn50DMA(@sid,@currdate)			
								begin
									select @ticker = ticker, @lastDataDate=lastdatadate from stock where stockID=@sid										
									select @audit = @ticker + ' crossed DWAP'
									exec saveAudit @currdate,  @audit, @sid, 'CROSSEDDWAP','I'
									declare @comment varchar(1000)
									select @comment =  'crossed DWAP'											
									exec @buyID = addbuyChannel @sid, 997, @currdate,@comment, null, 100, 'H', @currdate, 1	

									if @currdate < @yesterday
									begin
										--call the retro sells													
										if @buyID is not null and @BuyID != 0
											begin															
												exec @retval = runWatchesSell @BuyID												
											end														
										else
											begin
												if @buyID is null
													begin																
														select @audit='Could not find BuyID for stock in watchBuyAboveNewDWAP H section'
														Print @audit
													end
												else
													begin
														select @audit='Stock already held during this period in watchBuyAboveNewDWAP H section'												
													end										
												exec saveAudit @currdate, @audit, @sid
											end
									end
								end
					end				
	
			fetch next from scur into @sid, @ticker
			end
		close scur
		deallocate scur
			
	select @currdate = convert(varchar,dateadd(day,1,@currdate),101)
	end

set nocount off
/*

select * from stockdata where atwhen='3/5/2007' and stockID=1


select count(*) from stock where active=1



*/
