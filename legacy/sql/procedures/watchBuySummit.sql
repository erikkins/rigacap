-- SqlProcedure: [dbo].[watchBuySummit]

declare @watchID int
declare @ticker varchar(5)

declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuySummit'

exec addWatchHistory @watchID, @now
declare @52weekhighdate datetime
declare @52weekhigh money
declare @200dayhigh money
declare @currdate datetime
declare @currprice money
declare @currvolume bigint
declare @dwap money
declare @sid int

declare @buyID int
declare @50dmav bigint
declare @200Vol bigint

		select @currdate = @startdate
		select @sid = @stockID
		select @currprice = price, @currVolume = volume from stockdata where stockID=@sid and atwhen=@currdate
		if (@currprice is not null)
		BEGIN
			if dbo.fnIsPriceCrossDWAP(@sid,@currdate)=1 and dbo.isAccumulation(@sid,@currdate)=1
					bEGIN
					--only move on if the 50dmav is > 500K
					select @50dmav = dbo.fn50Volume(@sid, @currdate)
					if @50dmav >= 500000
						BeGiN					
							select @52weekhighdate = dbo.fn52WeekHighDate(@sid,@currdate)
							select @52weekhigh = price from stockdata where stockID=@sid and atwhen=@52weekhighdate
							if @52weekhigh > @currprice
								begin
								select @dwap = dbo.fnDWAP(@sid,@currdate)
								if @currprice > @dwap
									Begin
										select @200dayhigh = dbo.fn200DMA(@sid,@currdate)
										if @dwap > @200dayhigh
											BEGIN						
												select @200Vol = dbo.fn200Volume(@sid,@currdate)
												--print 'DWAP: ' + convert(varchar,@dwap) + '  50day: ' + convert(varchar,@50day) + '  50dayyest: ' + convert(varchar,@yest50day)
												if @currVolume > @200Vol
												begin
													exec @BuyID = AddBuyChannel @sid, -1000, @currdate, 'Summit Buy', null,100,'S',null,1
													exec saveAudit @now,  @audit, @stockID, 'SUMMITBUY', 'I'
													--select stockID, ticker, @currdate buydate
													--from stock where stockID=@sid
													
												end
											END
									end
								end
						EnD

					enD--ek

/* SECOND
			--only move on if the 50dmav is > 500K
			select @50dmav = dbo.fn50Volume(@sid, @currdate)
				if @50dmav >= 500000
					BeGiN					
							select @52weekhighdate = dbo.fn52WeekHighDate(@sid,@currdate)
							select @52weekhigh = price from stockdata where stockID=@sid and atwhen=@52weekhighdate
							if @52weekhigh > @currprice
								begin
								select @dwap = dbo.fnDWAP(@sid,@currdate)
								if @currprice > @dwap
									Begin
										select @200dayhigh = dbo.fn200DMA(@sid,@currdate)
										if @dwap > @200dayhigh
											BEGIN						
												select @200Vol = dbo.fn200Volume(@sid,@currdate)
												--print 'DWAP: ' + convert(varchar,@dwap) + '  50day: ' + convert(varchar,@50day) + '  50dayyest: ' + convert(varchar,@yest50day)
												if dbo.fnIsPriceCrossDWAP(@sid,@currdate)=1 and dbo.isAccumulation(@sid,@currdate)=1 and @currVolume > @200Vol
												begin
													exec @BuyID = AddBuyChannel @sid, -1000, @currdate, 'Summit Buy', null,100,'S',null,1
													exec saveAudit @now,  @audit, @stockID, 'SUMMITBUY', 'I'
													--select stockID, ticker, @currdate buydate
													--from stock where stockID=@sid
													
												end
											END
									end
								end
					EnD
*/
/* FIRST
			if @50dmav >= 500000
				BeGiN					
					select @52weekhighdate = dbo.fn52WeekHighDate(@sid,@currdate)
					select @52weekhigh = price from stockdata where stockID=@sid and atwhen=@52weekhighdate
					if @52weekhigh > @currprice
						begin
						select @dwap = dbo.fnDWAP(@sid,@currdate)
						if @currprice > @dwap
							Begin
								select @200dayhigh = dbo.fn200DMA(@sid,@currdate)
								if @dwap > @200dayhigh
									BEGIN						
										--if the last 52weekhigh was below the dwap, then BUY
										select top 1 @yesterday = atwhen
										from stockdata
										where stockID=@sid
										and atwhen < @currdate
										order by atwhen desc

										select @yestPrice = price
										from stockdata
										where stockID = @sid
										and atwhen = @yesterday

										select @50day = dbo.fn50DMA(@sid, @currdate)
										select @yest50day = dbo.fn50DMA(@sid, @yesterday)
										select @200Vol = dbo.fn200Volume(@sid,@currdate)
										--print 'DWAP: ' + convert(varchar,@dwap) + '  50day: ' + convert(varchar,@50day) + '  50dayyest: ' + convert(varchar,@yest50day)
										if @50day >= @dwap and @yest50day < @dwap and @currprice > @yestPrice and @currVolume > @200Vol
										begin
											exec @BuyID = AddBuyChannel @sid, -1000, @currdate, 'Summit Buy', null,100,'S',null,1
											exec saveAudit @now,  @audit, @stockID, 'SUMMITBUY', 'I'
											--exec findFirstSell @BuyID
											--select stockID, ticker, @currdate buydate
											--from stock where stockID=@sid
											
										end
									END
							end
						end
			EnD
*/





		END

return
